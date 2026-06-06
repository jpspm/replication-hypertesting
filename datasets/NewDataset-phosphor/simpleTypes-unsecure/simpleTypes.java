import edu.columbia.cs.psl.phosphor.runtime.MultiTainter; // @Phosphor
import edu.columbia.cs.psl.phosphor.runtime.Taint; // @Phosphor
import java.util.Arrays; // @Phosphor
public class simpleTypes {

    static class A {}
    static class B extends A {}
    static class C extends A {}

    public static int test(int secret) {
        secret = MultiTainter.taintedInt(secret, "secret_"); // @Phosphor
        int ret;
        A obj;
        if (secret != 0) {
            obj = new B();
            ret = 1;
        } else {
            obj = new C();
            ret = 0;
        }
        return ret;
    }

}