import edu.columbia.cs.psl.phosphor.runtime.MultiTainter; // @Phosphor
import edu.columbia.cs.psl.phosphor.runtime.Taint; // @Phosphor
import java.util.Arrays; // @Phosphor
public class simpleConditionalAssignmentEqual {

    public static int test(int secret) {
        secret = MultiTainter.taintedInt(secret, "secret_"); // @Phosphor
        int ret;
        ret = 1;
        return ret;
    }

    public static void main(String[] args) {
        int result = test(1);
        Taint t = MultiTainter.getTaint(result);
        if (t != null) {
            System.out.println("Phosphor: ret is tainted");
            System.out.println("Phosphor: taint labels " + t);
        }
    }

}