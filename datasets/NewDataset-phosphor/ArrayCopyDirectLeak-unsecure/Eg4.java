import edu.columbia.cs.psl.phosphor.runtime.MultiTainter; // @Phosphor
import edu.columbia.cs.psl.phosphor.runtime.Taint; // @Phosphor
import java.util.Arrays; // @Phosphor
public class Eg4 {

    public static int f(int h, int l) {
        h = MultiTainter.taintedInt(h, "h_"); // @Phosphor
        int ret;
        ret = l + h;
        return ret;
    }

    public static void main(String[] args) {
        int result = f(1, 0);
        Taint t = MultiTainter.getTaint(result);
        if (t != null) {
            System.out.println("Phosphor: ret is tainted");
            System.out.println("Phosphor: taint labels " + t);
        }
    }

}