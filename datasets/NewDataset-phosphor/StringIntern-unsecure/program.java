import edu.columbia.cs.psl.phosphor.runtime.MultiTainter; // @Phosphor
import edu.columbia.cs.psl.phosphor.runtime.Taint; // @Phosphor
import java.util.Arrays; // @Phosphor
public class program {

    public static int foo(int h) {
        h = MultiTainter.taintedInt(h, "h_"); // @Phosphor
        int ret;
        ret = h;
        return ret;
    }

    public static void main(String[] args) {
        int result = foo(1);
        Taint t = MultiTainter.getTaint(result);
        if (t != null) {
            System.out.println("Phosphor: ret is tainted");
            System.out.println("Phosphor: taint labels " + t);
        }
    }

}